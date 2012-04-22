"""What data are we processing?"""
data_dir = '2011_10_28\\2_color_u2os\\05_cells'
data_filename = 'u2os_488_z????.raw'
lake_filename = '01_lake_488.raw'
background_filename = '02_background.raw'
xPix, yPix, zPix, steps = 480, 480, 224, 224
background_zPix = zPix
extent = 20
animate = False #Set to "True" if you have to adjust 'extent'
scan_type = 'dmd'
scan_dimensions = (16, 14)
preframes = 0
num_harmonics = 3

##Don't edit below here
###############################################################################
import os, glob, pprint, numpy
import array_illumination

data_filename = os.path.join(os.getcwd(), data_dir, data_filename)
data_filenames_list = glob.glob(data_filename)
print "Data sources:", data_filename
print "Data filename list:"
for i in data_filenames_list:
    print '.  ' + i
lake_filename = os.path.join(os.getcwd(), data_dir, lake_filename)
background_filename = os.path.join(os.getcwd(), data_dir, background_filename)
print "Calibration source:", lake_filename
print "Background source:", background_filename

"""Find a set of shift vectors which characterize the illumination"""
print "\nDetecting illumination lattice parameters..."
(lattice_vectors, shift_vector, offset_vector,
 intensities_vs_galvo_position, background_frame
 ) = array_illumination.get_lattice_vectors(
     filename_list=data_filenames_list,
     lake=lake_filename, bg=background_filename,
     use_lake_lattice=True,
     xPix=xPix, yPix=yPix, zPix=zPix, bg_zPix=background_zPix,
     preframes=preframes,
     extent=extent, #Important to get this right.
     num_spikes=300,
     tolerance=3.5,
     num_harmonics=num_harmonics,
     outlier_phase=1.,
     calibration_window_size=10,
     scan_type=scan_type,
     scan_dimensions=scan_dimensions,
     verbose=False, #Useful for debugging
     display=False, #Useful for debugging
     animate=animate, #Useful to see if 'extent' is right
     show_interpolation=False, #Fairly low-level debugging
     show_calibration_steps=False, #Useful for debugging
     show_lattice=True) #Very useful for checking validity
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

num_processes = 2
for f in data_filenames_list:
    print
    print f
    sim_image = array_illumination.enderlein_image_parallel(
        data_filename=f,
        lake_filename=lake_filename, background_filename=background_filename,
        xPix=xPix, yPix=yPix, zPix=zPix, steps=steps, preframes=preframes,
        lattice_vectors=lattice_vectors,
        offset_vector=offset_vector,
        shift_vector=shift_vector,
        new_grid_x=new_grid_x, new_grid_y=new_grid_y,
        num_processes = num_processes,
        window_footprint=10,
        aperture_size=3,
        make_widefield_image=True,
        make_confocal_image=False, #Broken, for now
        verbose=True,
        show_steps=False, #For debugging
        show_slices=False, #For debugging
        intermediate_data=False, #Memory hog, for stupid reasons, leave 'False'
        normalize=False, #Of uncertain merit, leave 'False' probably
        display=False
        )
