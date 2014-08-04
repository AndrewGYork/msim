import os
from time import sleep
import numpy as np
import matplotlib.pyplot as plt
from scipy.ndimage import gaussian_filter
from scipy.interpolate import interp1d
import simple_tif
import convert_units

len_linker = 250 #Waveform zero, voltage nonzero
len_deadzone = 250 #Waveform zero, voltage zero

iteration = 0
while True:
    new_input_voltage_filename = 'input_voltage_to_mirror_%02i.tif'%(iteration)
    result_filename = 'result_from_chip_%02i.tif'%(iteration)
    if (os.path.exists(result_filename) and
        os.path.exists(new_input_voltage_filename)):
        iteration += 1
    else:
        iteration -= 1
        previous_input_voltage_filename = (
            'input_voltage_to_mirror_%02i.tif'%(iteration))
        previous_result_filename = 'result_from_chip_%02i.tif'%(iteration)
        if not os.path.exists(previous_result_filename):
            raise UserWarning("Result data not found")
        break

print iteration
print "Previous:"
print ' ', previous_input_voltage_filename
print ' ', previous_result_filename
print 'Creating:'
print ' ', new_input_voltage_filename


"""
Load everything in optimization units
"""
previous_input_voltage = simple_tif.tif_to_array(
    previous_input_voltage_filename).ravel().astype(np.float64)
previous_input_voltage = (
    convert_units.voltage_mirror_units_to_optimization_units(
        previous_input_voltage))
if iteration == 0:
    """
    The pre-optimizer isn't allowed to write voltages during the
    linker; this optimizer is. Pad with zeros.
    """
    previous_input_voltage = np.concatenate((previous_input_voltage,
                                             np.zeros(len_linker)))
desired_result = simple_tif.tif_to_array('expected_result.tif'
                                          ).ravel().astype(np.float64)
desired_result = np.concatenate((desired_result,
                                 np.zeros(len_deadzone, dtype=np.float64)))
assert desired_result.size == previous_input_voltage.size + len_deadzone
result_image = simple_tif.tif_to_array(previous_result_filename
                                       ).astype(np.float64)[0, :, :]
"""
Use subpixel interpolation to estimate the measured result trace
"""
measured_result = []
for row in range(result_image.shape[0]):
    find_my_argmax = gaussian_filter(result_image[row, :], sigma=5)
    search_here = np.argmax(find_my_argmax)
    interp_coords = np.arange(-1, 2)
    interp_values = find_my_argmax[search_here - 1:search_here + 2]
    my_fit = np.poly1d(np.polyfit(
        interp_coords, interp_values, deg=2))
    true_max = -my_fit[1] / (2.0*my_fit[2]) + search_here - 1010.15
    measured_result.append(true_max)
measured_result = np.array(measured_result).ravel()
measured_result = interp1d( #Resample to a new pixel density
    np.arange(0, measured_result.size, 1, dtype=np.float64),
    -measured_result,
    kind='linear',
    bounds_error=False,
    fill_value=measured_result[-1]
    )(np.arange(0, measured_result.size, 0.5, dtype=np.float64)
      )[:desired_result.size]
##measured_result[3850:3888] = -1032
measured_result = convert_units.result_mirror_units_to_optimization_units(
    measured_result)
residual = desired_result - measured_result
impulse_response = simple_tif.tif_to_array('impulse_response.tif'
                                           ).ravel().astype(np.float64)
assert impulse_response.size >= desired_result.size

##plt.figure()
##plt.subplot(3, 1, 1)
##plt.plot(previous_input_voltage, label='Voltage')
##plt.plot(desired_result, label='Desired')
##plt.plot(measured_result, label='Measured')
##plt.grid('on')
##plt.legend()
##plt.subplot(3, 1, 2)
##plt.plot(residual, label='Residual error')
##plt.grid('on')
##plt.legend()
##plt.subplot(3, 1, 3)
##plt.plot(impulse_response, label='Impulse response')
##plt.grid('on')
##plt.legend()
##plt.show()

def H(v):
    """
    Pad and blur the input to get the expected output
    """
    return np.convolve(v, impulse_response
                       )[:desired_result.size] #This assumes zero boundaries

def H_transpose(r):
    """
    Blur-transpose (time-reversed blur) and crop the residual to get
    something to correct the estimate.
    """
    return np.convolve(
        r, impulse_response[::-1])[
            -len_deadzone - previous_input_voltage.size:
            -len_deadzone]

num_iterations = 1000000
regularization = 0.01
correction_voltage = residual.copy()[:previous_input_voltage.size]
plt.figure()
for i in range(num_iterations):
    print "Iteration", i
    predicted_result = H(correction_voltage)
    correction_factor = regularization * H_transpose(residual -
                                                     predicted_result)
    correction_voltage += correction_factor

    plt.clf()
    plt.plot(correction_voltage, label='Voltage')
    plt.plot(residual, '.', ms=4, label='Desired residual')
    plt.plot(predicted_result, '-', label='Expected residual')
    plt.grid()
    plt.legend()
    plt.savefig('./comparison/%06i.png'%i)
    plt.clf()
    plt.plot(residual - predicted_result)
    plt.grid()
    plt.savefig('./differences/%06i.png'%i)

    voltage_to_save = convert_units.voltage_optimization_units_to_mirror_units(
        previous_input_voltage + 0.8 * correction_voltage)
    for tries in range(10):
        try:
            simple_tif.array_to_tif(
                voltage_to_save.astype(np.float32
                                       ).reshape(voltage_to_save.size, 1, 1),
                new_input_voltage_filename)
            break
        except IOError:
            sleep(0.05)
    else:
        print "Seriously? C'mon, Windows."
