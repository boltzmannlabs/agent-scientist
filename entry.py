import multiprocessing
from sci_cli.main import main

if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()