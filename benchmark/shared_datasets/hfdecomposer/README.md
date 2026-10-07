# HFDecomposer

This replication package contains the implementation of HFDecomposer and the dataset in our experiments.

## Implementation
The implementation of HFDecomposer can be found at the folder `./source_code`.

`./source_code/main.py` shows the overview of decomposing and refactoring. `./source_code/example.ipynb` provides an usage example for generating decomposition suggestion. 

## Dataset
`./dataset` contains the dataset used in our paper.
- File `filtered_data.csv` is a summary for the ground_truth.
- Folder `header_files` contains the original header file and the sub-header files that were refactored by the developers for each project.
- Folder `openssl_7436` is an example project. The decomposition suggestion for the header file `include/openssl/modes.h` is shown in `./source_code/example.ipynb`.
      
## Results

HFDecomposer is an LLM-based approach. We conducted experiments on GPT-4o and DeepSeek-V3. 