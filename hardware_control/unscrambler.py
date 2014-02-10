import numpy as np
from simple_tif import array_to_tif, tif_to_array

def unscramble(num_im, num_slices, input_file_name, output_file_name):
    interlaced_image_raw = tif_to_array(input_file_name).astype(np.float64)

    ##check to make sure I am divisible by num_im
    num_columns = interlaced_image_raw.shape[-1]
    extra_pixels = num_columns % num_im
    
    if extra_pixels == 0:
        interlaced_image = interlaced_image_raw
    else:
        interlaced_image = interlaced_image_raw[:, :, :num_columns-extra_pixels]
            
    zstacks = num_im * num_slices
    yrows = interlaced_image.shape[-2]
    xcolumns = (interlaced_image.shape[-1]/num_im)

    
    sorted_image_stack = np.zeros((zstacks, yrows, xcolumns), 
                                  dtype= interlaced_image.dtype)
    for j in range(num_slices):
        ##l2r
        for i in range(num_im):
            sorted_image_stack[(j*num_im) + i, :, :] = interlaced_image[j, :, i::num_im]
        ##r2l
        for i in range(num_im):
            sorted_image_stack[(j*num_im) + i, :, :] = interlaced_image[j, :, i::num_im]                
    
    array_to_tif(sorted_image_stack.astype(np.float32), output_file_name)
    
    print "Image 1:", sorted_image_stack.shape, sorted_image_stack.dtype

if __name__ == "__main__":
    
    unscramble(9, 100, 'BigPendulumStack.tif', 'You Have Been UnscrambledStack1.tif')
    
