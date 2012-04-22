import sys, os, pprint, numpy, pylab
import array_illumination

pylab.close('all')

"""What data are we processing?"""
data_dir = 'test_stack'
data_filename = 'u2os_488_z0015.raw'
lake_filename = '01_lake_488.raw'
background_filename = '02_background.raw'
xPix, yPix, zPix, steps = 480, 480, 224, 224
background_zPix = zPix
extent = 20
num_harmonics = 3
animate = False
scan_type = 'dmd'
scan_dimensions = (16, 14)
preframes = 0


##Don't edit below here
data_filename = os.path.join(os.getcwd(), data_dir, data_filename)
lake_filename = os.path.join(os.getcwd(), data_dir, lake_filename)
background_filename = os.path.join(os.getcwd(), data_dir, background_filename)
print "Data source:", data_filename
print "Calibration source:", lake_filename
print "Background source:", background_filename

"""Find a set of shift vectors which characterize the illumination"""
print "\nDetecting illumination lattice parameters..."
(lattice_vectors, shift_vector, offset_vector,
 intensities_vs_galvo_position, background_frame
 ) = array_illumination.get_lattice_vectors(
     filename=data_filename, lake=lake_filename, bg=background_filename,
     use_lake_lattice=True,
     xPix=xPix, yPix=yPix, zPix=zPix, bg_zPix=background_zPix,
     preframes=preframes,
     extent=extent, #Important to get this right. '20' for 1024/1344
     num_spikes=300,
     tolerance=3.5,
     num_harmonics=num_harmonics,
     outlier_phase=1.,
     calibration_window_size=10,
     scan_type=scan_type,
     scan_dimensions=scan_dimensions,
     verbose=True, #Useful for debugging
     display=False, #Useful for debugging
     animate=animate, #Useful to see if 'extent' is right
     show_interpolation=False, #Fairly low-level debugging
     show_calibration_steps=False, #Useful for debugging
     show_lattice=False) #Very useful for checking validity
print "Lattice vectors:"
for v in lattice_vectors:
    print v
print "Shift vector:"
pprint.pprint(shift_vector)
print "Initial position:"
print offset_vector

"""Define a new Cartesian grid for Enderlein's trick:"""
new_grid_x = numpy.linspace(0, xPix-1, 2*xPix)
new_grid_y = numpy.linspace(0, yPix-1, 2*yPix)

sim_image = array_illumination.enderlein_image(
    data_filename=data_filename,
    xPix=xPix, yPix=yPix, zPix=zPix, steps=steps, preframes=preframes,
    lattice_vectors=lattice_vectors,
    offset_vector=offset_vector,
    shift_vector=shift_vector,
    intensities_vs_galvo_position=intensities_vs_galvo_position,
    background_frame=background_frame,
    new_grid_x=new_grid_x, new_grid_y=new_grid_y,
    window_footprint=10,
    aperture_size=3,
    make_widefield_image=True,
    make_confocal_image=False, #Broken, for now
    verbose=True,
    show_steps=False, #For debugging
    show_slices=False, #For debugging
    intermediate_data=False, #Memory hog, for stupid reasons, leave 'False'
    normalize=False #Of uncertain merit, leave 'False' probably
    )
