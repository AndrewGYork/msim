import sys
import time
import ctypes
import Queue
import multiprocessing as mp
import numpy as np
try:
    from scipy import ndimage
except ImportError:
    ndimage = None
import pyglet
import simple_tif
from arrayimage import ArrayInterfaceImage
try:
    from camera_child_process import camera_child_process
except ImportError:
    camera_child_process = None

"""
Acquiring and displaying data from a camera is a common problem our
lab has to solve. This module provides a common framework for parallel
acquisition, display, and saving at their own paces, without enforced
synchronization.
"""

log = mp.get_logger()
info = log.info
debug = log.debug
if sys.platform == 'win32':
    clock = time.clock
else:
    clock = time.time

class Image_Data_Pipeline:
    def __init__(
        self,
        num_buffers=100,
        buffer_shape=(60, 256, 512),
        ):
        """
        Allocate a bunch of 16-bit buffers for image data, and a few
        8-bit buffers for display data.
        """
        self.buffer_shape = buffer_shape
        self.buffer_size = int(np.prod(buffer_shape))
        self.num_data_buffers = num_buffers
        
        self.data_buffers = [mp.Array(ctypes.c_uint16, self.buffer_size)
                             for b in range(self.num_data_buffers)]
        self.idle_data_buffers = range(self.num_data_buffers)
        
        self.accumulation_buffers = [mp.Array(ctypes.c_uint16, self.buffer_size)
                                     for b in range(2)]

        display_buffer_size = np.prod(buffer_shape[1:])
        self.display_buffers = [mp.Array(ctypes.c_uint16, display_buffer_size)
                                for b in range(2)]

        """
        Launch the child processes that make up the pipeline
        """
        if camera_child_process is None:
            print "Couldn't load camera_child_process.py."
            print "Using default dummy camera."
        self.camera = Data_Pipeline_Camera(
            data_buffers=self.data_buffers, buffer_shape=self.buffer_shape)
        self.accumulation = Data_Pipeline_Accumulation(
            data_buffers=self.data_buffers, buffer_shape=self.buffer_shape,
            accumulation_buffers=self.accumulation_buffers,
            input_queue=self.camera.output_queue)
        self.file_saving = Data_Pipeline_File_Saving(
            data_buffers=self.data_buffers, buffer_shape=self.buffer_shape,
            input_queue=self.accumulation.output_queue)
        
        self.projection = Data_Pipeline_Projection(
            buffer_shape=self.buffer_shape,
            display_buffers=self.display_buffers,
            accumulation_buffers=self.accumulation_buffers,
            accumulation_buffer_input_queue=
            self.accumulation.accumulation_buffer_output_queue,
            accumulation_buffer_output_queue=
            self.accumulation.accumulation_buffer_input_queue)
        self.display = Data_Pipeline_Display(
            display_buffers=self.display_buffers,
            buffer_shape=self.buffer_shape,
            display_buffer_input_queue=
            self.projection.display_buffer_output_queue,
            display_buffer_output_queue=
            self.projection.display_buffer_input_queue)
        return None
    
    def load_data_buffers(
        self, N, file_saving_info=None, collect_buffers=True, timeout=0):
        """
        'file_saving_info' is None, or a list of dicts. Each dict is a
        set of arguments to simple_tif.array_to_tif().
        """
        if file_saving_info is not None:
            if len(file_saving_info) != N:
                raise UserWarning(
                    "If file saving info is provided, it must match the number" +
                    " of buffers loaded.")
        """
        Feed the pipe!
        """
        for i in range(N):
            """
            Get an idle buffer
            """
            for tries in range(10):
                try:
                    idle_buffer = self.idle_data_buffers.pop(0)
                    break
                except IndexError:
                    if collect_buffers:
                        if tries > 0:
                            time.sleep(timeout * 0.1)                            
                        self.collect_data_buffers()
            else:
                raise UserWarning("Timeout exceeded, no buffer available")
            """
            Load the buffer into the queue, along with file saving
            info if appropriate
            """
            permission_slip = {'which_buffer': idle_buffer}
            if file_saving_info is not None:
                permission_slip['file_info'] = file_saving_info.pop(0)
            self.camera.input_queue.put(permission_slip)
        return None

    def collect_data_buffers(self):
        while True:
            try:
                strip_me = self.file_saving.output_queue.get_nowait()
            except Queue.Empty:
                break
            self.idle_data_buffers.append(strip_me['which_buffer'])
            info("Buffer %i idle"%(self.idle_data_buffers[-1]))
        return None
    
    def set_buffer_shape(self, buffer_shape):
        """
        You don't have to use the whole buffer! If you want to make a
        buffer with more pixels than the original one, though, you
        should make a new Image_Data_Pipeline.
        """
        assert len(buffer_shape) == 3
        for s in buffer_shape:
            assert s > 0
        if np.prod(buffer_shape) > self.buffer_size:
            raise UserWarning("If you want a buffer larger than the original" +
                              " buffer size, close this Image_Data_Pipeline" +
                              " and make a new one.")
        self.buffer_shape = buffer_shape
        while len(self.idle_data_buffers) < len(self.data_buffers):
            self.collect_data_buffers()
            time.sleep(0.01)
        for p in (self.camera,
                  self.accumulation,
                  self.file_saving,
                  self.projection,
                  self.display):
            p.commands.send(('set_buffer_shape', {'shape': buffer_shape}))
            while True:
                if p.commands.poll():
                    p.commands.recv()
                    break
        return None
    
    def set_display_intensity_scaling(
        self, scaling, display_min=None, display_max=None):
        args = locals()
        args.pop('self')
        self.display.commands.send(('set_intensity_scaling', args))
        return None

    def get_display_intensity_scaling(self):
        return self.display.get_intensity_scaling()

    def withdraw_display(self):
        self.display.commands.send(('withdraw', {}))

    def check_children(self):
        return {'Camera': self.camera.child.is_alive(),
                'Accumulation': self.accumulation.child.is_alive(),
                'File Saving': self.file_saving.child.is_alive(),
                'Projection': self.projection.child.is_alive(),
                'Display': self.display.child.is_alive()}

    def close(self):
        self.camera.input_queue.put(None)
        self.accumulation.input_queue.put(None)
        self.file_saving.input_queue.put(None)
        self.projection.display_buffer_input_queue.put(None)
        self.projection.accumulation_buffer_input_queue.put(None)
        self.display.display_buffer_input_queue.put(None)
        self.camera.child.join()
        self.accumulation.child.join()
        self.file_saving.child.join()
        self.projection.child.join()
        self.display.child.join()
        return None

class Data_Pipeline_Camera:
    def __init__(
        self,
        data_buffers,
        buffer_shape,
        input_queue=None,
        output_queue=None,
        ):
        if input_queue is None:
            self.input_queue = mp.Queue()
        else:
            self.input_queue = input_queue

        if output_queue is None:
            self.output_queue = mp.Queue()
        else:
            self.output_queue = output_queue

        self.commands, self.child_commands = mp.Pipe()

        self.child = mp.Process(
            target=camera_child_process,
            args=(data_buffers, buffer_shape,
                  self.input_queue, self.output_queue,
                  self.child_commands),
            name='Camera')
        self.child.start()
        return None
    
if camera_child_process is None:
    def camera_child_process(
        data_buffers,
        buffer_shape,
        input_queue,
        output_queue,
        commands,
        ):
        buffer_size = np.prod(buffer_shape)
        data = [np.zeros(buffer_shape, dtype=np.uint16)
                for i in data_buffers]
        for i, d in enumerate(data):
            d.fill(int((2**16 - 1) * (i + 1.0) / len(data)))
        data_idx = -1
        while True:
            if commands.poll():
                cmd, args = commands.recv()
                commands.send(None)
                if cmd == 'set_buffer_shape':
                    buffer_shape = args['shape']
                    buffer_size = np.prod(buffer_shape)
                continue
            try:
                permission_slip = input_queue.get_nowait()
            except Queue.Empty:
                time.sleep(0.001)
                continue
            if permission_slip is None:
                break #We're done
            else:
                """Fill the buffer with something"""
                process_me = permission_slip['which_buffer']
                info("start buffer %i"%(process_me))
                with data_buffers[process_me].get_lock():
                    a = np.frombuffer(data_buffers[process_me].get_obj(),
                                      dtype=np.uint16)[:buffer_size
                                                       ].reshape(buffer_shape)
    ##                a.fill(1)
                    data_idx += 1
                    data_idx = data_idx %len(data)
                    a[:] = data[data_idx][:buffer_shape[0],
                                          :buffer_shape[1],
                                          :buffer_shape[2]]
    ##            time.sleep(0.013)
                info("end buffer %i"%(process_me))
                output_queue.put(permission_slip)
        return None

class Data_Pipeline_Accumulation:
    def __init__(
        self,
        data_buffers,
        buffer_shape,
        accumulation_buffers,
        input_queue=None,
        output_queue=None,
        ):
        if input_queue is None:
            self.input_queue = mp.Queue()
        else:
            self.input_queue = input_queue

        if output_queue is None:
            self.output_queue = mp.Queue()
        else:
            self.output_queue = output_queue

        self.commands, self.child_commands = mp.Pipe()
        self.accumulation_buffer_input_queue = mp.Queue()
        self.accumulation_buffer_output_queue = mp.Queue()

        self.child = mp.Process(
            target=accumulation_child_process,
            args=(data_buffers, buffer_shape, accumulation_buffers,
                  self.input_queue, self.output_queue, self.child_commands,
                  self.accumulation_buffer_input_queue,
                  self.accumulation_buffer_output_queue),
            name='Accumulation')
        self.child.start()
        return None

def accumulation_child_process(
    data_buffers,
    buffer_shape,
    accumulation_buffers,
    data_buffer_input_queue,
    data_buffer_output_queue,
    commands,
    accumulation_buffer_input_queue,
    accumulation_buffer_output_queue,
    ):
    buffer_size = np.prod(buffer_shape)
    current_accumulation_buffer = 0
    num_accumulated = 0
    accumulation_buffer_input_queue.put(1)
    accumulation_buffer_occupied = False
    while True:
        if commands.poll():
            cmd, args = commands.recv()
            if cmd == 'set_buffer_shape':
                buffer_shape = args['shape']
                buffer_size = np.prod(buffer_shape)
                commands.send(buffer_shape)
            continue
        if accumulation_buffer_occupied:
            try: #Check for a pending accumulation buffer
                switch_to_me = accumulation_buffer_input_queue.get_nowait()
            except Queue.Empty: #Keep accumulating to the current buffer
                pass
            else: #We got one! Switch to using the fresh accumulation buffer
                accumulation_buffer_output_queue.put(
                    int(current_accumulation_buffer))
                current_accumulation_buffer = switch_to_me
                info("Sending accumulation buffer with %i timepoint(s)"%(
                    num_accumulated))
                accumulation_buffer_occupied = False
                num_accumulated = 0
        try: #Check for a pending data buffer
            permission_slip = data_buffer_input_queue.get_nowait()
        except Queue.Empty: #Nothing pending. Back to square one.
            time.sleep(0.001)
            continue
        if permission_slip is None: #Poison pill. Quit!
            break
        else:
            """Accumulate the data buffer"""
            process_me = permission_slip['which_buffer']
            info("start buffer %i"%(process_me))
            with data_buffers[process_me].get_lock():
                data = np.frombuffer(
                    data_buffers[process_me].get_obj(),
                    dtype=np.uint16)[:buffer_size].reshape(buffer_shape)
                with accumulation_buffers[
                    current_accumulation_buffer].get_lock():
                    a_b = np.frombuffer(accumulation_buffers[
                        current_accumulation_buffer].get_obj(),
                        dtype=np.uint16)[:buffer_size].reshape(buffer_shape)
                    if accumulation_buffer_occupied: #Accumulate
                        np.maximum(data, a_b, out=a_b)
                    else: #First accumulation; copy.
                        a_b[:] = data
                        accumulation_buffer_occupied = True
            num_accumulated += 1
            data_buffer_output_queue.put(permission_slip)
            info("end buffer %i"%(process_me))
    return None

class Data_Pipeline_Projection:
    def __init__(
        self,
        buffer_shape,
        display_buffers,
        accumulation_buffers,
        accumulation_buffer_input_queue,
        accumulation_buffer_output_queue,
        ):

        self.accumulation_buffer_input_queue = accumulation_buffer_input_queue
        self.accumulation_buffer_output_queue = accumulation_buffer_output_queue

        self.commands, self.child_commands = mp.Pipe()
        self.display_buffer_input_queue = mp.Queue()
        self.display_buffer_output_queue = mp.Queue()

        self.child = mp.Process(
            target=projection_child_process,
            args=(buffer_shape, display_buffers, accumulation_buffers,
                  self.child_commands,
                  self.display_buffer_input_queue,
                  self.display_buffer_output_queue,
                  self.accumulation_buffer_input_queue,
                  self.accumulation_buffer_output_queue),
            name='Projection')
        self.child.start()
        return None

def projection_child_process(
    buffer_shape,
    display_buffers,
    accumulation_buffers,
    commands,
    display_buffer_input_queue,
    display_buffer_output_queue,
    accumulation_buffer_input_queue,
    accumulation_buffer_output_queue,
    ):
    buffer_size = np.prod(buffer_shape)
    display_buffer_size = np.prod(buffer_shape[1:])
    while True:
        try: #Get a pending display buffer
            fill_me = display_buffer_input_queue.get_nowait()
        except Queue.Empty:
            time.sleep(0.001)
            continue #Don't bother with other stuff!
        if fill_me is None: #Poison pill. Quit!
            break
        else: 
            info("Display buffer %i received"%(fill_me))
            while True:
                if commands.poll():
                    info("Command received")
                    cmd, args = commands.recv()
                    if cmd == 'set_buffer_shape':
                        buffer_shape = args['shape']
                        buffer_size = np.prod(buffer_shape)
                        display_buffer_size = np.prod(buffer_shape[1:])
                        commands.send(buffer_shape)
                    continue
                try: #Now get a pending accumulation buffer
                    project_me = accumulation_buffer_input_queue.get_nowait()
                except Queue.Empty: #Nothing pending. Keep trying.
                    time.sleep(0.001)
                    continue
                if project_me is None: #Poison pill. Quit!
                    break
                else:
                    """Project the accumulation buffer"""
                    info("start accumulation buffer %i"%(project_me))
                    with accumulation_buffers[project_me].get_lock():
                        acc = np.frombuffer(
                            accumulation_buffers[project_me].get_obj(),
                            dtype=np.uint16)[:buffer_size].reshape(buffer_shape)
                        with display_buffers[fill_me].get_lock():
                            disp = np.frombuffer(
                                display_buffers[fill_me].get_obj(),
                                dtype=np.uint16)[:display_buffer_size
                                                 ].reshape(buffer_shape[1:])
                            np.amax(acc, axis=0, out=disp) #Project
                    info("end accumulation buffer %i"%(project_me))
                    accumulation_buffer_output_queue.put(project_me)
                    info("Returning display buffer %i"%(fill_me))
                    display_buffer_output_queue.put(fill_me)
                    break #Go back and look for the next display buffer
    return None

class Data_Pipeline_Display:
    def __init__(
        self,
        display_buffers,
        buffer_shape,
        display_buffer_input_queue,
        display_buffer_output_queue,
        ):
        self.display_buffer_input_queue = display_buffer_input_queue
        self.display_buffer_output_queue = display_buffer_output_queue

        self.commands, self.child_commands = mp.Pipe()
        self.display_intensity_scaling_queue = mp.Queue()
        self.display_intensity_scaling = ('linear', 0, 2**16 - 1)

        self.child = mp.Process(
            target=display_child_process,
            args=(display_buffers, buffer_shape,
                  self.display_buffer_input_queue,
                  self.display_buffer_output_queue,
                  self.child_commands,
                  self.display_intensity_scaling_queue),
            name='Display')
        self.child.start()
        return None

    def get_intensity_scaling(self):
        try:
            self.display_intensity_scaling = (
                self.display_intensity_scaling_queue.get_nowait())
        except Queue.Empty:
            pass
        return self.display_intensity_scaling

def display_child_process(
    display_buffers,
    buffer_shape,
    input_queue,
    output_queue,
    commands,
    display_intensity_scaling_queue,
    ):
    args = locals()
    display = Display(**args)
    display.run()
    return None

class Display:
    def __init__(
        self,
        display_buffers,
        buffer_shape,
        input_queue,
        output_queue,
        commands,
        display_intensity_scaling_queue):
        
        self.display_buffers = display_buffers
        self.buffer_shape = buffer_shape
        self.display_buffer_size = np.prod(buffer_shape[1:])
        self.input_queue = input_queue
        self.output_queue = output_queue
        self.commands = commands
        self.display_intensity_scaling_queue = display_intensity_scaling_queue

        self.set_intensity_scaling('linear', display_min=0, display_max=2**16-1)

        self.current_display_buffer = 1
        self.switch_buffers(0)
        self.convert_to_8_bit()

        self.make_window()

        update_interval_seconds = 0.025
        pyglet.clock.schedule_interval(self.update, update_interval_seconds)
        return None

    def run(self):
        """
        Eventually put code here to deal with closing and re-opening the window.
        """
        pyglet.app.run()
        return None

    def quit(self):
        pyglet.app.exit()
        return None

    def update(self, dt):
        if self.commands.poll():
            self.execute_external_command()
            return None
        try:
            switch_to_me = self.input_queue.get_nowait()
        except Queue.Empty:
            return None
        if switch_to_me is None: #Poison pill. Quit!
            self.quit()
        else:
            self.switch_buffers(switch_to_me)
            self.convert_to_8_bit()
        return None

    def make_window(self):
        screen_width, screen_height = self._get_screen_dimensions()

        self.window = pyglet.window.Window(
            min(screen_width//2, screen_height),
            min(screen_width//2, screen_height),
            caption='Display', resizable=True)
        self.default_image_scale = min(
            (screen_width//2) * 1.0 / self.image.width,
            screen_height * 1.0 / self.image.height)
        self.image_scale = self.default_image_scale
        self.image_x, self.image_y = 0, 0
        @self.window.event
        def on_draw():
            self.window.clear()
            self.image.blit(
                x=self.image_x, y=self.image_y,
                height=int(self.image.height * self.image_scale),
                width=int(self.image.width * self.image_scale))

        """
        Allow the user to pan and zoom the image
        """
        @self.window.event
        def on_mouse_drag(x, y, dx, dy, buttons, modifiers):
            if buttons == pyglet.window.mouse.LEFT:
                self.image_x += dx
                self.image_y += dy
            self._enforce_panning_limits()

        @self.window.event
        def on_mouse_scroll(x, y, scroll_x, scroll_y):
            old_image_scale = self.image_scale
            self.image_scale *= 1.3**(scroll_y)
            """
            No sense letting the user make the image underfill the window
            """
            while (self.image.width * self.image_scale < self.window.width and
                   self.image.height * self.image_scale < self.window.height):
                self.image_scale = min(
                    self.window.width * 1.0 / self.image.width,
                    self.window.height * 1.0 / self.image.height)
            """
            Might as well set some sane zoom limits, too.
            """
            if self.image_scale < 0.01:
                self.image_scale = 0.01
            if self.image_scale > 300:
                self.image_scale = 300
            """
            Center the origin of the zoom on the mouse coordinate.
            This was kinda thinky to figure out, don't fuck with this lightly.
            """
            zoom = self.image_scale * 1.0 / old_image_scale
            self.image_x = self.image_x * zoom + x * (1 - zoom)
            self.image_y = self.image_y * zoom + y * (1 - zoom)
            self._enforce_panning_limits()
        
        @self.window.event
        def on_mouse_release(x, y, button, modifiers):
            self.last_mouse_release = (x, y, button, clock())

        @self.window.event
        def on_mouse_press(x, y, button, modifiers):
            if hasattr(self, 'last_mouse_release'):
                if (x, y, button) == self.last_mouse_release[:-1]:
                    """Same place, same button"""
                    if clock() - self.last_mouse_release[-1] < 0.2:
                        """We got ourselves a double-click"""
                        self.image_scale = self.default_image_scale
                        self.image_x = 0
                        self.image_y = 0
                        w, h = self._get_screen_dimensions()
                        edge_length = min(w//2, h)
                        self.window.width = edge_length
                        self.window.height = edge_length            
        """
        We don't want 'escape' or 'quit' to quit the pyglet
        application, just withdraw it. The parent application should
        control when pyglet quits.
        """
        @self.window.event
        def on_key_press(symbol, modifiers):
            if symbol == pyglet.window.key.ESCAPE:
                self.window.set_visible(False)
                return pyglet.event.EVENT_HANDLED
        @self.window.event
        def on_close():
            self.window.set_visible(False)
            return pyglet.event.EVENT_HANDLED

    def execute_external_command(self):
        """
        The command should be a 2-tuple. The first element of the
        tuple is a string naming the command. The second element of
        the tuple is a dict of arguments to the command.
        """
        cmd, args = self.commands.recv()
        if cmd == 'set_intensity_scaling':
            self.set_intensity_scaling(**args)
        elif cmd == 'get_intensity_scaling':
            self.commands.send((self.intensity_scaling,
                                self.display_min,
                                self.display_max))
        elif cmd == 'set_buffer_shape':
            self.buffer_shape = args['shape']
            self.display_buffer_size = np.prod(self.buffer_shape[1:])
            if hasattr(self, 'display_data_16'):
                self.display_data_16 = self.display_data_16[
                    :self.buffer_shape[1],
                    :self.buffer_shape[2]]
            if hasattr(self, 'display_data_8'):
                self.display_data_8 = np.empty(self.buffer_shape[1:],
                                               dtype=np.uint8)
            np.take(self.lut, self.display_data_16, out=self.display_data_8)
            self.image = ArrayInterfaceImage(self.display_data_8,
                                             allow_copy=False)
            pyglet.gl.glTexParameteri( #Reset to no interpolation
                pyglet.gl.GL_TEXTURE_2D,
                pyglet.gl.GL_TEXTURE_MAG_FILTER,
                pyglet.gl.GL_NEAREST)
            self.window.set_size(self.image.width, self.image.height)
            self.commands.send(self.buffer_shape)
        elif cmd == 'withdraw':
            self.window.set_visible(False)
        else:
            raise UserWarning("Command not recognized: %s, %s"%(
                repr(cmd), repr(args)))
        return None

    def switch_buffers(self, switch_to_me):
        """
        Lock the new buffer, give up the old one.
        """
        info("Display buffer %i received"%(switch_to_me))
        self.display_buffers[switch_to_me].get_lock().acquire()
        try:
            self.display_buffers[self.current_display_buffer
                                 ].get_lock().release()
        except AssertionError:
            info("First time releasing lock")
            pass #First time through, we don't have the lock yet.
        self.output_queue.put(int(self.current_display_buffer))
        info("Display buffer %i loaded to projection process"%(
            self.current_display_buffer))
        self.current_display_buffer = int(switch_to_me)
        self.display_data_16 = np.frombuffer(
            self.display_buffers[self.current_display_buffer].get_obj(),
            dtype=np.uint16)[:self.display_buffer_size
                             ].reshape(self.buffer_shape[1:])
        return None

    def convert_to_8_bit(self):
        """
        Convert 16-bit display data to 8-bit using a lookup table.
        """
        if self.intensity_scaling == 'autoscale':
            self.display_min = self.display_data_16.min()
            self.display_max = self.display_data_16.max()
            self._make_linear_lookup_table()
        elif self.intensity_scaling == 'median_filter_autoscale':
            filtered_image = ndimage.filters.median_filter(
                self.display_data_16, size=3, output=self.filtered_image)
            self.display_min = self.filtered_image.min()
            self.display_max = self.filtered_image.max()
            self._make_linear_lookup_table()
        if not hasattr(self, 'display_data_8'):
            self.display_data_8 = np.empty(
                self.buffer_shape[1:], dtype=np.uint8)
        np.take(self.lut, self.display_data_16, out=self.display_data_8)
        try:
            self.display_intensity_scaling_queue.get_nowait()
        except Queue.Empty:
            pass
        self.display_intensity_scaling_queue.put(
            (self.intensity_scaling, self.display_min, self.display_max))
        self.image = ArrayInterfaceImage(self.display_data_8, allow_copy=False)
        pyglet.gl.glTexParameteri( #Reset to no interpolation
                pyglet.gl.GL_TEXTURE_2D,
                pyglet.gl.GL_TEXTURE_MAG_FILTER,
                pyglet.gl.GL_NEAREST)
        if hasattr(self, 'window'):
            if not self.window.visible:
                self.window.set_visible(True)
        return None

    def set_intensity_scaling(self, scaling, display_min, display_max):
        if scaling == 'linear':
            self.intensity_scaling = 'linear'
            if display_min is not None and display_max is not None:
                if display_min < 0:
                    display_min = 0
                if display_min > (2**16 - 2):
                    display_min = (2**16 - 2)
                if display_max <= display_min:
                    display_max = display_min + 1
                if display_max > (2**16 - 1):
                    display_max = 2**16 - 1
                self.display_min = display_min
                self.display_max = display_max
                self._make_linear_lookup_table()
        elif scaling == 'autoscale':
            self.intensity_scaling = 'autoscale'
            self.display_min = self.display_data_16.min()
            self.display_max = self.display_data_16.max()
            self._make_linear_lookup_table()
        elif scaling == 'median_filter_autoscale':
            if ndimage is None:
                info("Median filter autoscale requires Scipy. " +
                     "Using min/max autoscale.")
                self.intensity_scaling = 'autoscale'
                self.display_min = self.display_data_16.min()
                self.display_max = self.display_data_16.max()
            else:
                self.intensity_scaling = 'median_filter_autoscale'
                if not hasattr(self, 'filtered_image'):
                    self.filtered_image = np.empty(
                        self.buffer_shape[1:], dtype=np.uint16)
                filtered_image = ndimage.filters.median_filter(
                    self.display_data_16, size=3, output=self.filtered_image)
                self.display_min = self.filtered_image.min()
                self.display_max = self.filtered_image.max()
            self._make_linear_lookup_table()
        else:
            raise UserWarning("Scaling not recognized:, %s"%(repr(scaling)))
        if hasattr(self, 'display_data_16'):
            self.convert_to_8_bit()
        return None
    
    def _make_linear_lookup_table(self):
        """
        Waaaaay faster than how I was doing it before.
        http://stackoverflow.com/q/14464449/513688
        """
        if not hasattr(self, '_lut_start'):
            self._lut_start = np.arange(2**16, dtype=np.uint16)
        if not hasattr(self, '_lut_intermediate'):
            self._lut_intermediate = self._lut_start.copy()
        if not hasattr(self, 'lut'):
            self.lut = np.empty(2**16, dtype=np.uint8)
        np.clip(self._lut_start, self.display_min, self.display_max,
                out=self._lut_intermediate)
        self._lut_intermediate -= self.display_min
        self._lut_intermediate //= (
            self.display_max - self.display_min + 1.) / 256.
        self.lut[:] = self._lut_intermediate.view(np.uint8)[::2]
        return None

    def _get_screen_dimensions(self):
        plat = pyglet.window.Platform()
        disp = plat.get_default_display()
        screen = disp.get_default_screen()
        return screen.width, screen.height

    def _enforce_panning_limits(self):
        if self.image_x < (self.window.width -
                           self.image.width*self.image_scale):
            self.image_x = (self.window.width -
                            self.image.width*self.image_scale)
        if self.image_y < (self.window.height -
                           self.image.height*self.image_scale):
            self.image_y = (self.window.height -
                            self.image.height*self.image_scale)
        if self.image_x > 0:
            self.image_x = 0
        if self.image_y > 0:
            self.image_y = 0
        return None

class Data_Pipeline_File_Saving:
    def __init__(
        self,
        data_buffers,
        buffer_shape,
        input_queue=None,
        output_queue=None,
        ):
        if input_queue is None:
            self.input_queue = mp.Queue()
        else:
            self.input_queue = input_queue

        if output_queue is None:
            self.output_queue = mp.Queue()
        else:
            self.output_queue = output_queue

        self.commands, self.child_commands = mp.Pipe()

        self.child = mp.Process(
            target=file_saving_child_process,
            args=(data_buffers, buffer_shape,
                  self.input_queue, self.output_queue, self.child_commands),
            name='File Saving')
        self.child.start()
        return None

def file_saving_child_process(
    data_buffers,
    buffer_shape,
    input_queue,
    output_queue,
    commands,
    ):
    buffer_size = np.prod(buffer_shape)
    while True:
        if commands.poll():
            cmd, args = commands.recv()
            if cmd == 'set_buffer_shape':
                buffer_shape = args['shape']
                buffer_size = np.prod(buffer_shape)
                commands.send(buffer_shape)
            continue
        try:
            permission_slip = input_queue.get_nowait()
        except Queue.Empty:
            time.sleep(0.001)
            continue
        if permission_slip is None:
            break
        else:
            process_me = permission_slip['which_buffer']
            info("start buffer %i"%(process_me))
            if 'file_info' in permission_slip:
                """
                We only save the file if we have information for it.
                """
                info("saving buffer %i"%(process_me))
                """Copy the buffer to disk"""
                file_info = permission_slip['file_info']
                with data_buffers[process_me].get_lock():
                    a = np.frombuffer(data_buffers[process_me].get_obj(),
                                      dtype=np.uint16)[:buffer_size
                                                       ].reshape(buffer_shape)
                    simple_tif.array_to_tif(a, **file_info)
            info("end buffer %i"%(process_me))
            output_queue.put(permission_slip)
    return None

if __name__ == '__main__':
    import logging
    logger = mp.log_to_stderr()
    logger.setLevel(logging.INFO)

    idp = Image_Data_Pipeline(
        num_buffers=5,
        buffer_shape=(10, 2048, 2060))
    idp.camera.commands.send(
        ('apply_settings',
         {'trigger': 'auto trigger',
          'region_of_interest': (-1, -1, 10000, 10000),
          'exposure_time_microseconds': 10000}))
    idp.set_display_intensity_scaling(scaling='autoscale')
    print idp.camera.commands.recv()
    while True:
        try:
            print idp.check_children()
            idp.collect_data_buffers()
            idp.load_data_buffers(len(idp.idle_data_buffers))
            raw_input('Press Enter to continue...')
##            idp.set_buffer_shape((idp.buffer_shape[0],
##                                  idp.buffer_shape[1],
##                                  idp.buffer_shape[2] - 10))
        except KeyboardInterrupt:
            break
    idp.close()
