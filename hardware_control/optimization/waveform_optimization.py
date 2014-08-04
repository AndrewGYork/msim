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

camera_exposures = 4
live_facets = 4
flyback_facets = 1
len_ramp = 42
len_facet = 250
len_undefined = len_facet - len_ramp
len_linker = len_facet
len_voltage = (camera_exposures *
               (live_facets + flyback_facets) *
               (len_undefined + len_ramp))
len_response = (camera_exposures * live_facets * len_ramp +
                len_linker)
len_flyback = flyback_facets * len_facet
assert impulse_response.size >= (len_voltage + len_linker)

def H(voltage):
    """
    Pad, blur and crop the input to get the output
    """
    assert voltage.size == len_voltage
    blurred_voltage = np.convolve(voltage, impulse_response) #This pads!
    response = np.zeros(len_response)
    voltage_cursor = 0
    response_cursor = 0
    for ex in range(camera_exposures):
        for f in range(live_facets):
            voltage_cursor += len_undefined
            response[response_cursor:
                     response_cursor + len_ramp
                   ] = blurred_voltage[voltage_cursor:
                                       voltage_cursor + len_ramp]
            voltage_cursor += len_ramp
            response_cursor += len_ramp
        voltage_cursor += len_flyback
    response[response_cursor:
             response_cursor + len_linker
             ] = blurred_voltage[voltage_cursor:
                                 voltage_cursor + len_linker]
    return response
    
def H_transpose(residual):
    """
    Crop-transpose (pad), blur-transpose (time-reversed blur), and
    then pad-transpose (crop) the residual to get something that's the
    right dimensions to correct the estimate.
    """
    assert residual.size == len_response
    correction = np.zeros(len_voltage + len_linker, dtype=np.float64) #This pads
    residual_cursor = 0
    correction_cursor = 0
    for ex in range(camera_exposures):
        for f in range(live_facets):
            correction_cursor += len_undefined
            correction[correction_cursor:
                       correction_cursor + len_ramp
                       ] = residual[residual_cursor:
                                    residual_cursor + len_ramp]
            residual_cursor += len_ramp
            correction_cursor += len_ramp
        correction_cursor += len_flyback
    correction[correction_cursor:
               correction_cursor + len_linker
               ] = residual[residual_cursor:
                            residual_cursor + len_linker]
    blurred_correction = np.convolve(correction, #This blurs
                                     impulse_response[::-1]
                                     )[-len_linker - len_voltage:
                                       -len_linker] #This crops!
    return blurred_correction

input_voltage = np.zeros(len_voltage, dtype=np.float64)
desired_result = np.zeros(len_response, dtype=np.float64)
time = np.zeros_like(desired_result)
rise_per_ramp = 1
input_voltage_cursor = 0
desired_result_cursor = 0
for ex in range(camera_exposures):
    for f in range(live_facets):
        input_voltage[
            input_voltage_cursor:
            input_voltage_cursor + len_undefined
            ] = np.linspace(
                input_voltage[input_voltage_cursor - 1], #Hacky :(
                input_voltage[input_voltage_cursor - 1],
                len_undefined)
        input_voltage_cursor += len_undefined
        if f == 0:
            start_point = 0
        else:
            start_point = desired_result[desired_result_cursor - 1]
        desired_result[
            desired_result_cursor:
            desired_result_cursor + len_ramp
            ] = np.linspace(
                start_point,
                start_point + rise_per_ramp,
                len_ramp)
        time[
            desired_result_cursor:
            desired_result_cursor + len_ramp
            ] = np.arange(input_voltage_cursor,
                          input_voltage_cursor + len_ramp)
        desired_result_cursor += len_ramp

        input_voltage[
            input_voltage_cursor:
            input_voltage_cursor + len_ramp
            ] = np.linspace(
                input_voltage[input_voltage_cursor - 1],
                input_voltage[input_voltage_cursor - 1] + rise_per_ramp,
                len_ramp)
        input_voltage_cursor += len_ramp
    input_voltage[
        input_voltage_cursor:
        input_voltage_cursor + len_flyback
        ] = np.linspace(
            input_voltage[input_voltage_cursor - 1],
            0,
            len_flyback)
    input_voltage_cursor += len_flyback
desired_result[
    desired_result_cursor:
    desired_result_cursor + len_linker
    ] = 0
time[
    desired_result_cursor:
    desired_result_cursor + len_linker
    ] = np.arange(input_voltage_cursor,
                  input_voltage_cursor + len_linker)
desired_result_cursor += len_linker

input_voltage[
    input_voltage_cursor:
    input_voltage_cursor + len_linker
    ] = 0
input_voltage_cursor += len_linker

##plt.figure()
##plt.plot(input_voltage)
##plt.plot(time, desired_result, '.')
##plt.plot(time, H(input_voltage), '.')
##plt.show()

naive_input_voltage = input_voltage.copy()
print "Loading 'input_voltage.tif'..."
try:
    input_voltage = simple_tif.tif_to_array('input_voltage.tif'
                                                  ).ravel().astype(np.float64)
    print "Initial guess loaded"
except IOError:
    print "Loading failed. Using naive input voltage as initial guess."

iterations = 1000000
regularization = 0.05
plt.close('all')
plt.figure()
for i in range(iterations):
    print 'Iteration', i
    expected_result = H(input_voltage)
    
    expected_result_uncropped = np.convolve(
        input_voltage, impulse_response
        )[:input_voltage.size + len_linker]
    plt.clf()
    plt.plot(input_voltage)
    plt.plot(time, desired_result, '.', ms=4)
    plt.plot(expected_result_uncropped, '-')
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
    plt.plot(expected_result - desired_result)
    plt.grid()
    plt.savefig('./cropped_residuals/%06i.png'%i)    

    correction_factor = regularization * H_transpose(desired_result -
                                                     expected_result)
    input_voltage += correction_factor

    for tries in range(10):
        try:
            simple_tif.array_to_tif(
                input_voltage.astype(np.float32).reshape(
                    input_voltage.size, 1, 1),
                'input_voltage.tif')
            simple_tif.array_to_tif(
                expected_result_uncropped.astype(np.float32).reshape(
                    expected_result_uncropped.size, 1, 1),
                'expected_result.tif')
            break
        except:
            sleep(0.05)
    else:
        print "C'mon, Windows!"
            

plt.clf()
plt.plot(input_voltage)
plt.plot(time, desired_result, '.')
plt.plot(expected_result_uncropped, '.-')
plt.grid()

plt.figure()
plt.plot(input_voltage - naive_input_voltage, '.-')
plt.plot(expected_result_uncropped - naive_input_voltage, '.-')
plt.grid()
plt.show()


