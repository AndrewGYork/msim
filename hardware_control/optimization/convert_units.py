import numpy as np
import matplotlib.pyplot as plt
import simple_tif

scale = 2.2   ##2.2 and 600
shift = -560 #Mirror units

def voltage_optimization_units_to_mirror_units(v):
    return (v * scale +
            shift / 155.)
def voltage_mirror_units_to_optimization_units(v):
    return (v - (shift / 155.)) * 1.0 / scale
assert voltage_mirror_units_to_optimization_units(
    voltage_optimization_units_to_mirror_units(1)) == 1. #Careful! Floats!


def result_optimization_units_to_mirror_units(er):
    return (er * 155.) * scale + shift - 46. #Watch out for DC drift here
def result_mirror_units_to_optimization_units(er):
    return (((er - shift + 46.) * 1.0 / scale) ) / 155.
assert result_mirror_units_to_optimization_units(
    result_optimization_units_to_mirror_units(1)) == 1. #Careful! Floats!

if __name__ == '__main__':
    input_voltage = simple_tif.tif_to_array(
        'input_voltage.tif').astype(np.float64)
    expected_result = simple_tif.tif_to_array(
        'expected_result.tif').astype(np.float64)

    simple_tif.array_to_tif(
        voltage_optimization_units_to_mirror_units(input_voltage
                                                   ).astype(np.float32),
        'input_voltage_to_mirror.tif')
    simple_tif.array_to_tif(
        result_optimization_units_to_mirror_units(expected_result
                                                  ).astype(np.float32),
        'expected_result_from_chip.tif')

    plt.figure()
    plt.subplot(2, 1, 1)
    plt.plot(
        voltage_optimization_units_to_mirror_units(input_voltage).ravel(),
        label='Voltage to mirror')
    plt.grid('on')
    plt.legend()
    plt.subplot(2, 1, 2)
    plt.plot(
        result_optimization_units_to_mirror_units(
            expected_result).ravel(),
        label='Expected result')
    plt.legend()
    plt.grid('on')
    plt.show()
    
