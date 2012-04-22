import subprocess, sys, os
import pco, dmd, piezo

def snap(file_name='image.raw', save_path=None, preframes=3):
    """Take a single SIM frame without moving the piezo"""

    """To synchronize the DMD and the camera polling, we need two processes"""
    cmdString = """
import dmd, sys, time
dmd_handle = dmd.open_dmd()
sequence_id, num_frames = dmd.apply_settings(dmd_handle)
sys.stdout.write('%i'%(num_frames) + '\\n')
sys.stdout.flush()
cmd = raw_input()
time.sleep(0.15) #Give the camera time to arm
dmd.display_pattern(dmd_handle, sequence_id)
dmd.free_device(dmd_handle)
"""
    proc = subprocess.Popen( #python vs. pythonw on Windows?
        [sys.executable, '-c %s'%cmdString],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE)
    for i in range(8):
        print proc.stdout.readline(),
    num_images = int(proc.stdout.readline())
    print "Num. images:", num_images

    camera_handle = pco.open_camera()
    pco.apply_settings(camera_handle,
                       trigger="external trigger/software exposure control")
    print "Triggering DMD..."
    proc.stdin.write('Go!\n') #DMD should fire shortly after this
    pco.record_to_file(camera_handle, num_images=num_images,
                       file_name=file_name, save_path=save_path)
    pco.close_camera(camera_handle)
    print "DMD subprocess postmortem"
    report = proc.communicate()
    for i in report:
        print ' ' + i
    
def stack(
    z_positions = [0], file_basename='image.raw', save_path=None, preframes=3):
    """Take a sequence of SIM frames while moving the piezo"""

    """To synchronize the DMD and the camera polling, we need two processes"""
    cmdString = """
import dmd, sys, time
dmd_handle = dmd.open_dmd()
sequence_id, num_frames = dmd.apply_settings(dmd_handle)
sys.stdout.write('%i'%(num_frames) + '\\n')
sys.stdout.flush()
while True:
    cmd = raw_input()
    if cmd == 'done':
        break
    time.sleep(0.15) #Give the camera time to arm
    dmd.display_pattern(dmd_handle, sequence_id)
dmd.free_device(dmd_handle)
"""
    proc = subprocess.Popen( #python vs. pythonw on Windows?
        [sys.executable, '-c %s'%cmdString],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE)
    for i in range(8):
        print proc.stdout.readline(),
    num_images = int(proc.stdout.readline())
    print "Num. images:", num_images

    piezo_handle = piezo.open_piezo()
    camera_handle = pco.open_camera()
    pco.apply_settings(camera_handle,
                       trigger="external trigger/software exposure control")
    basename, ext = os.path.splitext(file_basename)
    for z in z_positions:
        z = float(z)
        piezo.move(piezo_handle, z)
        file_name = (
            basename +
            ('_z=%+05.2f'%(z*0.1)
             ).replace('.', 'p').replace('-', 'n').replace('+', '') +
            ext)
        print file_name
        print "Triggering DMD..."
        proc.stdin.write('Go!\n') #DMD should fire shortly after this
        pco.record_to_file(camera_handle, num_images=num_images,
                           file_name=file_name, save_path=save_path)
    piezo.close_piezo(piezo_handle)
    proc.stdin.write('done\n')
    pco.close_camera(camera_handle)
    print "DMD subprocess postmortem"
    report = proc.communicate()
    for i in report:
        print i

if __name__ == '__main__':
##    snap()
    stack(z_positions=range(-5, 40), file_basename='tubules.raw')

    
