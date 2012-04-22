"""What data are we processing?"""
data_dir = '2011_11_10\\01_worm_244fr_fine_steps'
data_filename = 'worm_c488_z????.raw'
lake_filename = 'lake_244fr_c488.raw'
background_filename = 'background_244fr.raw'
xPix, yPix, zPix, steps = 480, 480, 224, 224
background_zPix = zPix
extent = 20
animate = False #Temporarily set to "True" if you have to adjust 'extent'
scan_type = 'dmd'
scan_dimensions = (16, 14)
preframes = 0
num_harmonics = 3 #Default to 3, might have to lower to 2
use_all_lake_parameters = True #Useful if sample-based lattice detection fails

##Don't edit below here
###############################################################################
import os, glob, pprint, numpy
import array_illumination

data_filename = os.path.join(os.getcwd(), data_dir, data_filename)
data_filenames_list = sorted(glob.glob(data_filename))
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
     use_all_lake_parameters=use_all_lake_parameters,
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
     verbose=True, #Useful for debugging
     display=True, #Useful for debugging
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
new_grid_xrange = 0, xPix-1, 2*xPix
new_grid_yrange = 0, yPix-1, 2*yPix

num_processes = 6
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
        new_grid_xrange=new_grid_xrange, new_grid_yrange=new_grid_yrange,
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

if len(data_filenames_list) > 1:
    print "Joining enderlein and widefield images into stack..."
    enderlein_stack = numpy.zeros(
        (len(data_filenames_list), new_grid_xrange[2], new_grid_yrange[2]),
        dtype=numpy.float)
    widefield_stack = numpy.zeros(
        (len(data_filenames_list), new_grid_xrange[2], new_grid_yrange[2]),
        dtype=numpy.float)
    for i, d in enumerate(data_filenames_list):
        basename = os.path.splitext(d)[0]
        enderlein_image_name = basename + '_enderlein_image.raw'
        widefield_image_name = basename + '_widefield.raw'
        enderlein_stack[i, :, :] = numpy.fromfile(
            enderlein_image_name, dtype=numpy.float).reshape(
            new_grid_xrange[2], new_grid_yrange[2])
        widefield_stack[i, :, :] = numpy.fromfile(
            widefield_image_name, dtype=numpy.float).reshape(
            new_grid_xrange[2], new_grid_yrange[2])
    stack_basename = os.path.splitext(data_filename)[0].replace('?', '')
    enderlein_stack.tofile(os.path.join(
        data_dir, stack_basename + '_enderlein_stack.raw'))
    widefield_stack.tofile(os.path.join(
        data_dir, stack_basename + '_widefield_stack.raw'))
    e_notes = open(os.path.join(
        data_dir, stack_basename + '_enderlein_stack.txt'), 'wb')
    w_notes = open(os.path.join(
        data_dir, stack_basename + '_widefield_stack.txt'), 'wb')
    e_notes.write("Left/right: %i pixels\r\n"%(enderlein_stack.shape[2]))
    e_notes.write("Up/down: %i pixels\r\n"%(enderlein_stack.shape[1]))
    e_notes.write("Number of images: %i\r\n"%(enderlein_stack.shape[0]))
    e_notes.write("Data type: 64-bit real\r\n")
    e_notes.write("Byte order: Intel (little-endian))\r\n")
    e_notes.close()
    w_notes.write("Left/right: %i pixels\r\n"%(widefield_stack.shape[2]))
    w_notes.write("Up/down: %i pixels\r\n"%(widefield_stack.shape[1]))
    w_notes.write("Number of images: %i\r\n"%(widefield_stack.shape[0]))
    w_notes.write("Data type: 64-bit real\r\n")
    w_notes.write("Byte order: Intel (little-endian))\r\n")
    w_notes.close()
    print "Done joining."
