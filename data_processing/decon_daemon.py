import os, time
from decon import richardson_lucy_deconvolution

def pull_from_processing_queue(queue_name, temp_name):
    os.rename(queue_name, temp_name)
    with open(temp_name, 'rb') as f:
        processing_queue = f.readlines()
    os.remove(temp_name)
    try:
        process_this = processing_queue[0]
    except IndexError: #Empty queue
        return None
    with open(temp_name, 'wb') as f:
        for line in processing_queue[1:]:
            f.write(line)
    os.rename(temp_name, queue_name)
    return process_this

print "Use Ctrl-C to quit."
print "Ready to process..."
cwd = os.getcwd()
queue_name = os.path.join(os.getcwd(), 'processing_queue.txt')
temp_name = os.path.splitext(queue_name)[0] + '.temp'
while True:
    if os.path.exists(queue_name):
        process_this = pull_from_processing_queue(queue_name, temp_name)
        if process_this:
            info = {}
            for p in process_this.split(';'):
                k, v = p.strip().split('=')
                info[k] = v
            assert os.path.exists(info['filename'])
            assert os.path.splitext(info['filename'])[1] in (
                '.tif', '.tiff')
            print "Filename:", info['filename']
            sigma = [int(i) for i in info['sigma'].split(', ')]
            assert len(sigma) == 3
            print "Gaussian sigma for decon:", sigma
            iterations = int(info['iterations'])
            richardson_lucy_deconvolution(
                image_data=info['filename'],
                num_iterations=iterations,
                psf_data='gaussian',
                psf_sigma=sigma)
        else:
            print "Empty queue"
            print
    time.sleep(0.1)
        

