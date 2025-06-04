import subprocess

def get_tex_recon_bin():
    return ['/mvs-texturing/build/apps/texrecon/texrecon']

if __name__ == '__main__':
    # test
    command = get_tex_recon_bin()
    # '/mvs-texturing/build/apps/texrecon/texrecon' input.ply /output/path/textured_dense -d gmi -o gauss_clamping -t none --no_intermediate_results --num_threads=1
    subprocess.run(command)
