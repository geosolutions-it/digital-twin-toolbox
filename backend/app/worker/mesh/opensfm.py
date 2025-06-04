import subprocess

def get_OpenSfM_bin():
    return ['micromamba', 'run', '-n', 'opensfm', '/source/OpenSfM/bin/opensfm']

if __name__ == '__main__':
    # test
    command = get_OpenSfM_bin() + ['-h']
    subprocess.run(command)
