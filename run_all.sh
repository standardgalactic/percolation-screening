#!/bin/sh
# Reproduces every experiment in the paper. Run from the directory holding this file.
# Python 3.13 and a LaTeX installation are enough; only the pilot needs network access.
set -e
mkdir -p results
cd synthetic
python3 exp_threshold.py 3000 5                > ../results/threshold.txt
python3 exp_irreducibility.py 6 200 2          > ../results/irreducibility_m6.txt
python3 exp_irreducibility.py 7 150 1          > ../results/irreducibility_m7.txt
python3 exp_irreducibility.py 8 200 2          > ../results/irreducibility_m8.txt
python3 exp_calibration.py 1000 39 7 A         > ../results/calibration.txt
python3 exp_detection.py 40 199 11 A 1000 20   > ../results/detection_A.txt
python3 exp_mincut.py 40 99 5 1000 20 8 0.8    > ../results/mincut_sparse.txt
python3 exp_mincut.py 40 99 5 1000 20 8 3.0    > ../results/mincut_dense.txt
python3 exp_chokepoint.py 40 99 5 1000 20 8 0.8 > ../results/choke_sparse.txt
cd ../pilot
sh fetch_wheels.sh pilot_data
python3 -I pycallgraph.py ../results/pilot_virtualenv.json virtualenv distlib,filelock,platformdirs "$PWD/pilot_data/projA"
python3 -I pycallgraph.py ../results/pilot_gitpython.json gitpython gitdb,smmap "$PWD/pilot_data/projB"
