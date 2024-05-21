# BioInformatics Agent (BIA): Unleashing the Power of Large Language Models to Reshape Bioinformatics Workflow

## Installation
```sh
pip install -e .
```

### Examples

#### Search for samples
```sh
biagent geo_search "breast cancer"
```
#### Metadata extraction
Extract metadata from a chosen GEO sample, e.g.,
```sh
export DASHSCOPE_API_KEY="<your_api_key>"
biagent --model qwen-max metadata --gsm_id GSM3676057
```
The tool also supports processing multiple GEO samples provided in a line separated text file, e.g.,
```sh
head -n 1 gse_soft_files.txt
# /path/to/GSE132nnn/GSE132396/soft/GSE132396_family.soft.gz
biagent --model qwen-max metadata --soft_file_list gse_soft_files.txt --parallel 2 --output metadata.csv --cache_dir $PWD/cache
```
#### Count matrix reading
Read the count matrix from a chosen GEO sample, e.g.,
```sh
biagent --model qwen-max count_matrix --gsm_id GSM3676057 --output count_matrix.h5ad
```

## Roadmap
 - [ ] Add frontend and backend support for biagent