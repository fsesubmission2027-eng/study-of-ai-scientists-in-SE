# Replication Package for "Pinning is Futile: You Need More Than Local Dependency Versioning to Defend Against Supply Chain Attacks"

This replication package contains the complete dataset and analysis scripts to replicate all quantitative results from our FSE 2025 paper

* Hao He, Bogdan Vasilescu, and Christian Kästner. 2025. Pinning Is Futile: You Need More Than Local Dependency Versioning to Defend Against Supply Chain Attacks. Proc. ACM Softw. Eng. 2, FSE, Article FSE013 (July 2025), 24 pages. https://doi.org/10.1145/3715728

The package consists of:

- Jupyter notebooks and R markdown files to replicate Figures and Tables
- Curated datasets of npm packages and GitHub projects used to run panel regressions
- Additional scripts used in the study, for reference purposes
- Environment configuration files for reproducibility

## Obtaining the Artifact

The artifact is available from Zenodo: https://doi.org/10.5281/zenodo.14693233

### System Requirements

- Storage: >=2GB free disk space
- Memory: 16GB RAM recommended
- Operating systems: Windows, macOS, or Linux

## Environment Setup

To replicate results in the paper, a working Python 3.11+ environment and a working R 4.3.3+ environment are necessary. We recommend using Anaconda to setup the Python environment and install Jupyter Lab to run the notebooks.

### Python Environment Setup

```shell
# Create and activate the conda environment
conda env create -f environment.yml
conda activate pinfloat

# Launch Jupyter Lab
jupyter lab
```

### R Environment Setup

1. Install R 4.3.3+ from https://www.r-project.org/
2. Install RStudio from https://posit.co/download/rstudio-desktop/
3. Open the R markdown files in RStudio
4. Install required packages as prompted or run:

```r
install.packages(c("tidyverse", "plm", "ggplot2", "ggthemes", "texreg", "cowplot", "extrafont", "lmtest"))
```

## Main Datasets

1. **Abbreviations**:
    - `npm` stands for npm projects and `woc` stands for GitHub repositories used in the study (collected from World of Code, WoC); 
    - `all` stands for metrics computed from dependency graphs with development dependencies and `prod` stands for metrics computed from production dependencies only.

2. **Dataset Overview**: 
    - `data/samples_[npm/woc]_10000.csv` files describes the 10000 npm packages and GitHub repositories used in RQ1, respectively. 
    - Their version constraints can be found in `data/sample_dependencies_[npm/woc].csv` files, respectively. These data are used to compute Figure 1 in the paper. 

3. **Panel Regression (RQ1)**: 
    - The regression variables and outcome metrics are stored in `sample_depgraph_metrics_[woc/npm]_[all/prod].csv` files, respectivly. The raw `package-lock.json` files are way too large (~300GB), so we only include computed outcome metrics in the replication package.

4. **Network Simulations (RQ2)**: 
    - The computed risk metrics are in the `data/intervention` folder. These pre-computed metrics will be used by the Jupyter Notebook to replicate results in the paper, as computing them would require days on a modern computing server.
    - The raw dependency graph and the download data are in `data/depgraph_package_level.csv` and `data/npmjs.downloads.20220906.20230905.csv` files, respectively.

## Replicating Results

All results can be reproduced by running the following notebooks and R scripts in sequence. Each analysis step should take at most several minutes on a standard laptop.

1. **Dataset Overview**:
   * Run [dataset_statistics.ipynb](dataset_statistics.ipynb) - Replicates Table 2 and the error analysis results in RQ1.

2. **RQ1: State of Practice and Effectiveness of Pinning**:
   * Run [state_of_practice.ipynb](rq1_state_of_practice.ipynb) - Replicates Figure 1.
   * Run [rq1_effectiveness_of_pinning.ipynb](rq1_effectiveness_of_pinning.ipynb) - Replicates Table 3.
   * Open and run [rq1_regression.Rmd](rq1_regression.Rmd) in RStudio - Replicates Table 4, Figure 4, and other regression results in RQ1.

3. **RQ2: Alternative Interventions**:
   * Run [rq2_interventions.ipynb](rq2_interventions.ipynb) - Replicates RQ2 results, including Figure 6 and the numbers presented in the paper.

Additionally, we share all raw scripts used in this study in the `scripts/` folder. They are not directly replicable but we expect it to be useful for reference purposes. 

## License and Citation

This artifact is provided under the Apache 2.0 License. If you use this artifact in your research, please cite our paper:

```
@article{he2025pinning,
  title={Pinning Is Futile: You Need More Than Local Dependency Versioning to Defend Against Supply Chain Attacks},
  author={He, Hao and Vasilescu, Bogdan and K{\"a}stner, Christian},
  journal={Proc. ACM Softw. Eng.},
  volume={2},
  number={FSE},
  article={FSE013},
  year={2025},
  publisher={ACM},
  doi={10.1145/3715728}
}
```