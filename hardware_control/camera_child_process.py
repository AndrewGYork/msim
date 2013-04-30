import sys
import time
import Queue
import multiprocessing as mp
import numpy as np

"""
Allows image_data_pipeline.py to use different cameras. For now, only
the pco.edge works. In the future, we'll have multiple definitions of
camera_child_process() depending on what camera we want to use.
"""

log = mp.get_logger()
info = log.info
debug = log.debug
if sys.platform == 'win32':
    clock = time.clock
else:
    clock = time.time

def camera_child_process(
    data_buffers,
    buffer_shape,
    input_queue,
    output_queue,
    commands,
    ):
    """
    This version's suitable for the pco.edge camera.
    """
    import pco
    camera = pco.Edge()
    camera.apply_settings()
    camera.get_shutter_mode()
    camera.get_settings(verbose=False)
    camera.arm(num_buffers=3)
    camera._prepare_to_record_to_memory()
    preframes = 0
    while True:
        try:
            process_me = input_queue.get_nowait()
        except Queue.Empty:
            time.sleep(0.0005)
            continue
        if process_me is None:
            break #We're done
        else:
            """Fill the buffer with something"""
            info("start buffer %i"%(process_me))
            with data_buffers[process_me].get_lock():
                a = np.frombuffer(data_buffers[process_me].get_obj(),
                                  dtype=np.uint16).reshape(buffer_shape)
                camera.record_to_memory(
                    num_images=a.shape[0] + preframes,
                    preframes=preframes,
                    out=a)
            info("end buffer %i"%(process_me))
            output_queue.put(process_me)
    camera.close()
    return None
