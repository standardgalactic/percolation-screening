# Percolation Screening on the Cross-Boundary Shadow Graph

This repository accompanies a study of structural screening in software dependency and possible-call graphs. It contains the manuscript, the implementations of its synthetic experiments, the static-analysis pilot, and the saved experimental outputs.

The study examines how connectivity statistics on a cross-boundary shadow graph relate to concrete paths in the underlying directed graph. Degree-moment ratios and threshold statistics provide structural summaries; null ensembles support statistical comparisons; path witnesses, disjoint-route counts, and essential vertices support closer inspection. These quantities characterize the constructed graphs. They do not, by themselves, establish executable attack paths or exploitable vulnerabilities.

## Manuscript

The manuscript is available as [percolation_screening.pdf](paper/percolation_screening.pdf). Its LaTeX source, [percolation_screening.tex](paper/percolation_screening.tex), contains the bibliography within the same file. Rebuild the PDF from the repository root with:

```bash
cd paper
pdflatex percolation_screening.tex
pdflatex percolation_screening.tex
```

## Repository organization

The `paper/` directory contains the manuscript source and compiled PDF. The `synthetic/` directory contains the graph-generation, sampling, and validation code. The `pilot/` directory contains the pinned-package acquisition script and static possible-call graph extractor. The `results/` directory contains the saved text and JSON outputs used in the manuscript. The root-level [run_all.sh](run_all.sh) records the commands, parameters, and random seeds used for reproduction.

## Reproduction

Run the complete experimental workflow from the repository root:

```bash
bash run_all.sh
```

The synthetic experiments require Python 3 and use only the Python standard library. The workflow also requires a shell environment suitable for the supplied scripts. Rebuilding the manuscript requires a LaTeX installation with the packages declared in its source. Network access is needed to acquire the pilot wheels; analysis of already extracted source is local.

Calibration, detection, minimum-cut, and chokepoint experiments can each take several minutes in plain Python, depending on the machine. A script may perform substantial computation between printed updates. The saved outputs allow the reported results to be inspected without rerunning the complete suite.

## Synthetic validation

The shared implementation, [shadowlib.py](synthetic/shadowlib.py), provides the graph generator, constrained directed double-edge swap sampler, and common statistics. The validation scripts correspond, in order, to the manuscript's validation subsections: `exp_threshold.py`, `exp_irreducibility.py`, `exp_calibration.py`, `exp_detection.py`, `exp_mincut.py`, and `exp_chokepoint.py`.

These experiments examine connectivity thresholds, connectivity of the admissible state space under the sampling moves, test calibration, detection of planted structures, minimum cuts, and the distinction between edge-disjoint routes and shared vertex bottlenecks. Each script accepts command-line parameters; `run_all.sh` supplies the arguments and seeds used for the reported results.

The synthetic scripts are run from inside `synthetic/` without Python's isolated-mode flag, because they import `shadowlib.py` from that directory. For example, from the repository root:

```bash
cd synthetic
python3 exp_chokepoint.py
```

Consult `run_all.sh` for the exact reproduction invocation rather than assuming that a script's defaults reproduce the manuscript configuration.

## Static-analysis pilot

The acquisition script, [fetch_wheels.sh](pilot/fetch_wheels.sh), downloads seven pinned Python wheels and extracts each distribution into its own directory. The virtualenv pilot uses virtualenv 20.26.3, distlib 0.3.8, filelock 3.15.4, and platformdirs 4.2.2. The GitPython pilot uses GitPython 3.1.43, gitdb 4.0.11, and smmap 5.0.1.

The extractor, [pycallgraph.py](pilot/pycallgraph.py), parses source files with Python's `ast` module without importing or executing the analyzed packages. Run it with `python3 -I` so that the extracted source trees cannot be picked up through the usual script-directory or environment-based import paths. Its command-line interface is:

```text
python3 -I pycallgraph.py OUT.json APP_DIST DEP_DIST[,DEP_DIST...] SRC_ROOT
```

`SRC_ROOT` contains the extracted distribution directories. The exact project-specific commands are recorded in `run_all.sh`.

Each pilot report contains three graph variants. `strict` includes calls resolved by the extractor's static rules. `matched` additionally connects unresolved method calls to analyzed methods sharing the same name, subject to a candidate limit. `matched_filtered` restricts these additional matches to the caller's distribution and excludes a collection of common attribute names. The filtered variant is a sensitivity analysis, rather than a guarantee that every retained edge is correct or every excluded edge is spurious.

The JSON output records graph statistics, per-entry paths to designated process-execution sinks, edge-disjoint and internally vertex-disjoint route counts, essential intermediate vertices, and unresolved-call accounting. Route counts are capped at ten; a value of ten denotes at least ten routes. The selected entries are public-looking dependency functions and methods, rather than verified application entry points. Import-time sink calls are reported separately.

## Saved results

The `results/` directory contains `threshold.txt`, the three `irreducibility_m*.txt` files, `calibration.txt`, `detection_A.txt`, `mincut_sparse.txt`, `mincut_dense.txt`, and `choke_sparse.txt`. The real-project reports are [pilot_virtualenv.json](results/pilot_virtualenv.json) and [pilot_gitpython.json](results/pilot_gitpython.json).

The supplied reproduction commands specify the configurations associated with these outputs. A fresh pilot run on the pinned wheels reproduced the saved witness and function counts exactly, as reported for this experimental release.

## Interpretation and limitations

The synthetic experiments support evaluating the screening statistics under controlled graph constructions. Their detection rates depend on the background regime and planted structure. The irreducibility experiments also show that the permitted sampling moves need not connect every admissible degree class, so conclusions about null ensembles must respect the sampler's accessible state space and the test's construction.

The pilot demonstrates sensitivity to graph extraction. Unresolved receivers, name matching, and filtering can substantially change both aggregate statistics and reported paths. Static resolution is incomplete and can also produce incorrect edges; absence of a witness is therefore not evidence of absence of exposure. A reported witness establishes reachability within a particular extracted graph, with executable feasibility, attacker influence, and exploitability requiring separate source-level and behavioral evidence.
