from time import sleep
import numpy as np
import matplotlib.pyplot as plt
from scipy.ndimage import gaussian_filter
from scipy.interpolate import interp1d
import simple_tif

offset = 0
amplitude = 1.0 #Normalized later anyway
period = 300. #DAQ pix
phase = 0
decay_time = 1600 #DAQ pix
lag_time = 25 #DAQ pix

t = np.arange(200*period, dtype=np.float64)
impulse_response = (offset +
                    amplitude *
                    np.sin(t * 2*np.pi/period + phase) *
                    np.exp(-t * 1.0 / decay_time))
lag_convolution = np.exp(-t/lag_time)
impulse_response = np.convolve(impulse_response, lag_convolution)
impulse_response /= impulse_response.sum()

impulse_response = impulse_response[:6000].copy()
t = t[:6000].copy() #Maybe leave room for a 'dead zone' too?

simple_tif.array_to_tif(
    impulse_response.astype(np.float32).reshape(impulse_response.size, 1, 1),
    'impulse_response.tif')

camera_exposures = 2 #Has to be an even number
sweeps_per_exposure = 4
len_warmup = 200
len_sweep = 79 #DAQ pix
len_ramp = 60 #DAQ pix
len_undefined = len_sweep - len_ramp
len_voltage = (len_warmup +
               (camera_exposures *
                sweeps_per_exposure *
                len_sweep))
len_response = (camera_exposures *
               sweeps_per_exposure *
               len_ramp)
assert impulse_response.size >= len_voltage

def H(voltage):
    """
    Pad, blur and crop the input to get the output
    """
    assert voltage.size == len_voltage
    blurred_voltage = np.convolve(voltage, impulse_response) #This pads!
    response = np.zeros(len_response)
    voltage_cursor = 0
    response_cursor = 0
    voltage_cursor += len_warmup #Warmup is undefined
    for ex in range(camera_exposures):
        for s in range(sweeps_per_exposure):
            voltage_cursor += len_undefined
            response[response_cursor:
                     response_cursor + len_ramp
                   ] = blurred_voltage[voltage_cursor:
                                       voltage_cursor + len_ramp]
            voltage_cursor += len_ramp
            response_cursor += len_ramp
    return response
    
def H_transpose(residual):
    """
    Crop-transpose (pad), blur-transpose (time-reversed blur), and
    then pad-transpose (crop) the residual to get something that's the
    right dimensions to correct the estimate.
    """
    assert residual.size == len_response
    correction = np.zeros(len_voltage, dtype=np.float64) #This pads
    residual_cursor = 0
    correction_cursor = 0
    correction_cursor += len_warmup #Warmup is undefined
    for ex in range(camera_exposures):
        for s in range(sweeps_per_exposure):
            correction_cursor += len_undefined
            correction[correction_cursor:
                       correction_cursor + len_ramp
                       ] = residual[residual_cursor:
                                    residual_cursor + len_ramp]
            residual_cursor += len_ramp
            correction_cursor += len_ramp
    blurred_correction = np.convolve(correction, #This blurs
                                     impulse_response[::-1]
                                     )[-len_voltage:] #This crops!
    return blurred_correction

input_voltage_sample = np.zeros(len_voltage, dtype=np.float64)
input_voltage_camera = np.zeros(len_voltage, dtype=np.float64)
desired_result_sample = np.zeros(len_response, dtype=np.float64)
desired_result_camera = np.zeros(len_response, dtype=np.float64)
time = np.zeros_like(desired_result_sample)
rise_per_ramp = 1
input_voltage_cursor = 0
desired_result_cursor = 0
"""
if camera exposure is even, need to switch sawtooth scan direction
and direction rescan direction across camera
"""
input_voltage_cursor += len_warmup #Warmup is undefined
for ex in range(camera_exposures):
    for s in range(sweeps_per_exposure):
        """
        Each sweep starts with an undefined region
        """
        if s == 0: #First sample sweep starts flat
            final_value = input_voltage_sample[input_voltage_cursor - 1]
        else: #Remaining sample sweeps start with flybacks
            if ex % 2 == 0: #Even exposures flyback down
                final_value = 0
            else: #Odd exposures flyback up
                final_value = rise_per_ramp
        input_voltage_sample[
            input_voltage_cursor:
            input_voltage_cursor + len_undefined
            ] = np.linspace(
                input_voltage_sample[input_voltage_cursor - 1], #Hacky :(
                final_value,
                len_undefined)
        input_voltage_camera[ #All camera sweeps start flat
            input_voltage_cursor:
            input_voltage_cursor + len_undefined
            ] = np.linspace(
                input_voltage_camera[input_voltage_cursor - 1], #Hacky :(
                input_voltage_camera[input_voltage_cursor - 1],
                len_undefined)
        input_voltage_cursor += len_undefined
        """
        Now we execute the defined portion of the sweep.

        First, desired results for the defined region:
        """
        if ex % 2 == 0: #Even sweeps start at zero and sweep up
            start_value = 0
            rise = rise_per_ramp
        else: #Odd sweeps start at 'rise_per_ramp' and sweep down
            start_value = rise_per_ramp
            rise = - rise_per_ramp
        desired_result_sample[
            desired_result_cursor:
            desired_result_cursor + len_ramp
            ] = np.linspace(
                start_value,
                start_value + rise,
                len_ramp)
        start_value = desired_result_camera[max(desired_result_cursor - 1, 0)]
        if ex % 2 == 0: #Even sweeps sweep up
            rise = rise_per_ramp
        else: #Odd sweeps sweep down
            rise = -rise_per_ramp
        desired_result_camera[
            desired_result_cursor:
            desired_result_cursor + len_ramp
            ] = np.linspace(
                start_value,
                start_value + rise,
                len_ramp)
        time[
            desired_result_cursor:
            desired_result_cursor + len_ramp
            ] = np.arange(input_voltage_cursor,
                          input_voltage_cursor + len_ramp)
        desired_result_cursor += len_ramp
        """
        Now input voltages for the defined region of the sweep:
        """
        if ex % 2 == 0: #Even exposures sweep up
            rise = rise_per_ramp
        else: #Odd exposures sweep down
            rise = -rise_per_ramp
        input_voltage_sample[
            input_voltage_cursor:
            input_voltage_cursor + len_ramp
            ] = np.linspace(
                input_voltage_sample[input_voltage_cursor - 1],
                input_voltage_sample[input_voltage_cursor - 1] + rise,
                len_ramp)
        input_voltage_camera[
            input_voltage_cursor:
            input_voltage_cursor + len_ramp
            ] = np.linspace(
                input_voltage_camera[input_voltage_cursor - 1],
                input_voltage_camera[input_voltage_cursor - 1] + rise,
                len_ramp)        
        input_voltage_cursor += len_ramp

##plt.figure()
##plt.plot(input_voltage_sample)
##plt.plot(time, desired_result_sample, '.')
##plt.plot(time, H(input_voltage_sample), '.')
##plt.plot(input_voltage_camera)
##plt.plot(time, desired_result_camera, '.')
##plt.plot(time, H(input_voltage_camera), '.')
##plt.show()

naive_input_voltage_sample = input_voltage_sample.copy()
naive_input_voltage_camera = input_voltage_camera.copy()
print "Loading 'input_voltage_sample.tif' and 'input_voltage_camera.tif'..."
try:
    input_voltage_sample = simple_tif.tif_to_array('input_voltage_sample.tif'
                                                   ).ravel().astype(np.float64)
    input_voltage_camera = simple_tif.tif_to_array('input_voltage_camera.tif'
                                                   ).ravel().astype(np.float64)
    print "Initial guess loaded"
except IOError:
    print "Loading failed. Using naive input voltages as initial guess."

iterations = 1000000
regularization = 0.1
plt.close('all')
plt.figure()
for i in range(iterations):
    print 'Iteration', i
    expected_result_sample = H(input_voltage_sample)
    expected_result_camera = H(input_voltage_camera)
    
    expected_result_sample_uncropped = np.convolve(
        input_voltage_sample, impulse_response
        )[:input_voltage_sample.size]
    expected_result_camera_uncropped = np.convolve(
        input_voltage_camera, impulse_response
        )[:input_voltage_camera.size]
    plt.clf()
    plt.plot(input_voltage_sample)
    plt.plot(time, desired_result_sample, '.', ms=4)
    plt.plot(expected_result_sample_uncropped, '-')
    plt.plot(input_voltage_camera)
    plt.plot(time, desired_result_camera, '.', ms=4)
    plt.plot(expected_result_camera_uncropped, '-')
    plt.grid()
    plt.savefig('./comparison/%06i.png'%i)
##    plt.clf()
##    plt.plot(input_voltage - naive_input_voltage)
##    plt.plot(expected_result_uncropped - naive_input_voltage)
##    plt.grid()
##    plt.savefig('./differences/%06i.png'%i)    
##    plt.clf()
##    plt.plot(expected_result_uncropped - naive_input_voltage)
##    plt.grid()
##    plt.savefig('./residuals/%06i.png'%i)
    plt.clf()
    plt.plot(expected_result_sample - desired_result_sample)
    plt.plot(expected_result_camera - desired_result_camera)
    plt.grid()
    plt.savefig('./cropped_residuals/%06i.png'%i)    

    correction_factor_sample = regularization * H_transpose(
        desired_result_sample -
        expected_result_sample)
    correction_factor_camera = regularization * H_transpose(
        desired_result_camera -
        expected_result_camera)
    input_voltage_sample += correction_factor_sample
    input_voltage_camera += correction_factor_camera

    input_voltage_sample[input_voltage_sample > 8.3] = 8.3
    input_voltage_sample[input_voltage_sample < -8.3] = -8.3

    for tries in range(10):
        try:
            simple_tif.array_to_tif(
                input_voltage_sample.astype(np.float32).reshape(
                    input_voltage_sample.size, 1, 1),
                'input_voltage_sample.tif')
            simple_tif.array_to_tif(
                input_voltage_camera.astype(np.float32).reshape(
                    input_voltage_camera.size, 1, 1),
                'input_voltage_camera.tif')
            simple_tif.array_to_tif(
                expected_result_sample_uncropped.astype(np.float32).reshape(
                    expected_result_sample_uncropped.size, 1, 1),
                'expected_result_sample.tif')
            simple_tif.array_to_tif(
                expected_result_camera_uncropped.astype(np.float32).reshape(
                    expected_result_camera_uncropped.size, 1, 1),
                'expected_result_camera.tif')
            break
        except:
            sleep(0.05)
    else:
        print "C'mon, Windows!"
            

plt.clf()
plt.plot(input_voltage_sample)
plt.plot(time, desired_result_sample, '.')
plt.plot(expected_result_sample_uncropped, '.-')
plt.plot(input_voltage_camera)
plt.plot(time, desired_result_camera, '.')
plt.plot(expected_result_camera_uncropped, '.-')
plt.grid()

plt.figure()
plt.plot(input_voltage_sample - naive_input_voltage_sample, '.-')
plt.plot(expected_result_sample_uncropped - naive_input_voltage_sample, '.-')
plt.plot(input_voltage_camera - naive_input_voltage_camera, '.-')
plt.plot(expected_result_uncropped_camera - naive_input_voltage_camera, '.-')
plt.grid()
plt.show()


