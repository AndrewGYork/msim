##import time
import logging
import multiprocessing as mp
import Tkinter as tk
##import numpy as np
from image_data_pipeline import Image_Data_Pipeline

##if sys.platform == 'win32':
##    clock = time.clock
##else:
##    clock = time.time

class GUI:
    def __init__(self):
        logger = mp.log_to_stderr()
        logger.setLevel(logging.INFO)
        self.data_pipeline = Image_Data_Pipeline(
            num_buffers=5,
            buffer_shape=(224, 480, 480))
        self.root = tk.Tk()

        self.menubar = tk.Menu(self.root)
        self.filemenu = tk.Menu(self.menubar, tearoff=0)
        self.filemenu.add_command(label="Exit", command=self.root.destroy)
        self.menubar.add_cascade(label="File", menu=self.filemenu)
        self.settingsmenu = tk.Menu(self.menubar, tearoff=0)
        self.settingsmenu.add_command(
            label="Display", command=self.open_display_settings_window)
        self.menubar.add_cascade(label="Settings", menu=self.settingsmenu)
        self.root.config(menu=self.menubar)

        frame = tk.Frame(self.root)
        frame.pack(side=tk.TOP)

        a = tk.Button(frame, text="QUIT", fg="red", command=frame.quit)
        a.pack(side=tk.LEFT)
        
        a.pack(side=tk.LEFT)
        a = tk.Button(
            frame, text="Load buffers",
            command=self.load_buffers)
        a.pack(side=tk.LEFT)
        
##        self.file_num = 0
##        a = tk.Button(
##            frame, text="Load buffers and save",
##            command=self.load_and_save)
##        a.pack(side=tk.LEFT)
##
        self.root.mainloop()
        self.data_pipeline.close()
        return None

    def load_buffers(self):
        self.data_pipeline.collect_data_buffers()
        self.data_pipeline.load_data_buffers(
            len(self.data_pipeline.idle_buffers))
        return None

##    def load_and_save(self):
##        self.data_pipeline.collect_data_buffers()
##        num_buffers = len(self.data_pipeline.idle_buffers)
##        file_info = []
##        for b in self.data_pipeline.idle_buffers:
##            file_info.append(
##                {'buffer_number': b,
##                 'outfile': 'image_%06i.tif'%(self.file_num)
##                 })
##            self.file_num += 1
##        self.data_pipeline.load_data_buffers(
##            num_buffers, file_saving_info=file_info)
##        return None

    def open_display_settings_window(self):
        try:
            self.display_settings_window.root.config()
        except (AttributeError, tk.TclError):
            self.display_settings_window = Display_Settings_Window(self)
        self.display_settings_window.root.lift()
        self.display_settings_window.root.focus_force()
        return None
        
class Display_Settings_Window:
    def __init__(self, parent):
        self.parent = parent
        self.root = tk.Toplevel(parent.root)
        self.root.wm_title("Display settings")
        self.root.bind("<Escape>", lambda x: self.root.destroy())

        frame = tk.Frame(self.root, relief=tk.SUNKEN, bd=4)
        frame.pack(side=tk.TOP, fill=tk.BOTH, expand=1)
        a = tk.Label(frame, text="Contrast settings:")
        a.pack(side=tk.TOP)
        subframe = tk.Frame(frame)
        subframe.pack(side=tk.TOP, fill=tk.BOTH)
        a = tk.Label(master=subframe, text='Lower\nlimit:')
        a.pack(side=tk.LEFT)
        self.display_min = Scale_Spinbox(
            subframe, from_=0, to=(2**16 - 1), initial_value=0)
        self.display_min.bind(
            "<<update>>", lambda x: self.set_scaling())
        self.display_min.pack(side=tk.LEFT, fill=tk.BOTH, expand=1)
        subframe = tk.Frame(frame)
        subframe.pack(side=tk.TOP, fill=tk.BOTH)
        a = tk.Label(master=subframe, text='Upper\nlimit:')
        a.pack(side=tk.LEFT)
        self.display_max = Scale_Spinbox(
            subframe, from_=0, to=(2**16 - 1), initial_value=(2**16 - 1))
        self.display_max.bind(
            "<<update>>", lambda x: self.set_scaling())
        self.display_max.pack(side=tk.LEFT, fill=tk.BOTH, expand=1)
        subframe = tk.Frame(frame)
        subframe.pack(side=tk.TOP, fill=tk.BOTH)
        a = tk.Label(master=subframe, text='Mode:')
        a.pack(side=tk.LEFT)
        self.scaling = tk.StringVar()
        self.old_scaling = 'linear'
        self.scaling.set('median_filter_autoscale')
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

        self.set_scaling()
        self.update_scaling()
        return None
    
    def set_scaling(self):
        self.parent.data_pipeline.set_display_intensity_scaling(
            self.scaling.get(),
            display_min=self.display_min.get(),
            display_max=self.display_max.get())
        return None

    def update_scaling(self):
        scaling, display_min, display_max = (
            self.parent.data_pipeline.get_display_intensity_scaling())
        self.scaling.set(scaling)
        self.display_min.set(display_min)
        self.display_max.set(display_max)
        self.root.after(400, self.update_scaling)
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


if __name__ == '__main__':
    GUI()
