data_filename = 'worm_c488_z????.raw'
data_dimensions = (480, 480)

############################################################
##Don't edit below here ####################################
############################################################
import glob, os, sys, Tkinter, tkFileDialog
import numpy
tkroot = Tkinter.Tk()
tkroot.withdraw()
data_folder = tkFileDialog.askdirectory(
    title=("Choose a data folder"))
tkroot.destroy()

data_filename = os.path.join(data_folder, data_filename)
data_filenames_list = sorted(glob.glob(data_filename))
if len(data_filenames_list) > 0:
    max_projections = numpy.zeros(
        ((len(data_filenames_list),) + data_dimensions), dtype=numpy.uint16)
    pix_per_slice = data_dimensions[0] * data_dimensions[1]
    for i, f in enumerate(data_filenames_list):
        print "Projecting:", os.path.split(f)[1]
        raw_data = numpy.fromfile(f, dtype=numpy.uint16)
        raw_data = raw_data.reshape(
            (raw_data.shape[0]/pix_per_slice,) + data_dimensions)
        max_projections[i, :, :] = raw_data.max(axis=0)

    max_projections.tofile(
        os.path.join(data_folder, 'stack_of_max_projections.raw'))

    notes = open(os.path.join(
        data_folder, 'stack_of_max_projections.txt'), 'wb')
    notes.write("Left/right: %i pixels\r\n"%(max_projections.shape[2]))
    notes.write("Up/down: %i pixels\r\n"%(max_projections.shape[1]))
    notes.write("Number of images: %i\r\n"%(max_projections.shape[0]))
    notes.write("Data type: 16-bit unsigned integers\r\n")
    notes.write("Byte order: Intel (little-endian))\r\n")
    notes.close()
else:
    print "No files found."
