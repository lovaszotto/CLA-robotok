import warnings
from robot import run

# Suppress only InsecureRequestWarning from urllib3
try:
    from urllib3.exceptions import InsecureRequestWarning
    warnings.simplefilter('ignore', InsecureRequestWarning)
except ImportError:
    pass

import sys
import os

def main():
    # Pass through all command-line arguments to robot
    args = sys.argv[1:]
    # Default to running version_check.robot if no args
    if not args:
        args = [os.path.join('resources', 'version_check.robot')]
    run(*args)

if __name__ == '__main__':
    main()
