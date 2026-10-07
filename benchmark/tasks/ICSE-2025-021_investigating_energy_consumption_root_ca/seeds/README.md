# Seeds for ICSE-2025-021 — EnergyDebug (Redis energy root-cause methodology)

> 论文正式标题：**Unveiling the Energy Vampires: A Methodology for Debugging Software Energy Consumption**（ICSE 2025，ACM SIGSOFT Distinguished Paper）。

## 下载数据（主机侧）

```bash
chmod +x download_energydebug.sh
./download_energydebug.sh
# 可选：只下 zip 不解压
# EXTRACT=0 ./download_energydebug.sh
# 可选：从 GitHub clone（可能缺大文件，完整 AE 请用 Zenodo）
# FETCH_MODE=git ./download_energydebug.sh
```

| 项 | 值 |
|----|-----|
| 主机路径 | `~/ai_scientist_inputs/shared_datasets/energydebug-icse2025` |
| Docker 挂载 | `/shared/energydebug-icse2025`（只读） |
| Agent 路径 | `dataset_candidate/energydebug-icse2025/` |
| 环境变量 | `ENERGYDEBUG_HOME`, `ENERGYDEBUG_DATA_HOME`, `ENERGYDEBUG_NOTEBOOK`, `ENERGYDEBUG_DOCKER_HOME` |
| Zenodo（latest） | https://doi.org/10.5281/zenodo.14856317 |
| Concept DOI | https://doi.org/10.5281/zenodo.14718382 |
| GitHub | https://github.com/enriquebarba97/EnergyDebug |

### 体积

| 项 | 大小 |
|----|------|
| Zenodo `EnergyDebug.zip` | **≈ 2.29 GiB（约 2.5 GB）**，`md5=5130b1717d323b6cc3f28daefef6f126` |
| 解压后 | 见 `.artifact_meta.txt` / `du -sh`（通常数 GB 级：energy CSV + uftrace） |

内容：`data/`（Redis / PostgreSQL / memcpy 的 energy、logs、tracing）、`docker/` 测量模板、`energydebug.ipynb` 分析笔记本。

## Docker / 容器环境

`task.env` + `seeds/container_setup.sh`：

- **Python venv**：`/opt/icse-2025-021-venv`
- **分析栈**：numpy / pandas / scipy / statsmodels / seaborn / scikit-posthocs + jupyter/nbconvert
- **不装** EnergiBridge / 特权 MSR：沙箱默认走 **已采集数据 + notebook 复现**

| 参数 | 论文测量机 | `task.env` |
|------|------------|------------|
| 计算 | Ryzen 9 7900X + 64GB + RTX 4090 | `MEMORY=32g`, `CPUS=8`，分析 CPU-only |
| GPU | 测量主机有 GPU | `REQUIRES_GPU=false` |
| 硬件计数器 | AMD MSR（新采集必需） | `REQUIRES_HARDWARE=false`（复用挂载 traces） |

## 启动 benchmark

```bash
./download_energydebug.sh
./run_aiscientist_benchmark.sh run
# 或 ./run_airesearcher_benchmark.sh run
```
